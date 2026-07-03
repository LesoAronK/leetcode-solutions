class Solution {
    public int diagonalSum(int[][] mat) {
        int n=mat.length;
        int psum=0;
        int ssum=0;
        for(int i=0;i<n;i++){
            psum=psum+mat[i][i];
            ssum=ssum+mat[i][n-i-1];
        }
        if(n%2!=0){
            return psum+ssum-mat[(n/2)][(n/2)];
        }
        return psum+ssum;
    }
}